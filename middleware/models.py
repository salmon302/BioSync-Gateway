# SPDX-License-Identifier: MIT
"""
SQLAlchemy ORM Models
Implements SRS §6.1 - Database Tables (ORM layer)
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, JSON, Boolean,
    ForeignKey, UniqueConstraint, CheckConstraint, ARRAY
)
from sqlalchemy.sql import func, text
from datetime import datetime
from database import Base


class User(Base):
    """User accounts for JWT authentication (SRS §6.1 users table)."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    scopes = Column(ARRAY(String), default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_login = Column(DateTime(timezone=True))


class Simulation(Base):
    """Pulse Engine simulation sessions (SRS §3.6)"""
    __tablename__ = "simulations"
    
    id = Column(Integer, primary_key=True)
    simulation_uid = Column(String(36), unique=True, nullable=False)
    patient_id = Column(String(255), nullable=False)
    engine_state = Column(JSON, nullable=False)
    status = Column(String(50), default="active", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    meta = Column("metadata", JSON)
    
    __table_args__ = (
        CheckConstraint(
            status.in_(["active", "paused", "completed"]),
            name="simulations_status_check"
        ),
    )


class TelemetrySession(Base):
    """WebSocket telemetry streaming sessions (SRS §3.1)"""
    __tablename__ = "telemetry_sessions"
    
    id = Column(Integer, primary_key=True)
    session_uid = Column(String(36), unique=True, nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"))
    patient_id = Column(String(255))
    start_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    end_time = Column(DateTime(timezone=True))
    status = Column(String(50), default="active")
    meta = Column("metadata", JSON)


class HumanFactorsMetric(Base):
    """uFMEA data collection (SRS FR-3.9)"""
    __tablename__ = "human_factors_metrics"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), nullable=False)
    event_type = Column(String(100), nullable=False)
    event_timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    latency_ms = Column(Integer)
    steps_count = Column(Integer)
    component = Column(String(100))
    meta = Column("metadata", JSON)


class Observation(Base):
    """FHIR Observation resources (telemetry data) (SRS §3.7)"""
    __tablename__ = "observations"
    
    id = Column(Integer, primary_key=True)
    observation_uid = Column(String(36), unique=True, nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"))
    patient_id = Column(String(255))
    observation_code = Column(String(100), nullable=False)
    value_quantity = Column(JSON, nullable=False)
    unit = Column(String(50))
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    raw_data = Column(JSON)
    filtered_data = Column(JSON)
    fhir_resource = Column(JSON, nullable=False)
    meta = Column("metadata", JSON)


class AuditLog(Base):
    """Append-only audit trail with hash chain (SRS FR-3.8)"""
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True)
    table_name = Column(String(255), nullable=False)
    operation = Column(String(10), nullable=False)
    record_id = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user_id = Column(String(255))
    previous_hash = Column(String(64))
    current_hash = Column(String(64), nullable=False)
    data = Column(JSON, nullable=False)
    # SRS FR-3.8.3: D_prev (prior row state) and R_i (change reason)
    previous_state = Column(JSON, nullable=True)
    reason = Column(Text, nullable=True)


class Patient(Base):
    """Simulated patient demographics (synthetic, no PHI) (SRS §6.1)"""
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True)
    patient_uid = Column(String(36), unique=True, nullable=False)
    synthetic_id = Column(String(255), unique=True, nullable=False)
    demographics = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DeviceMetric(Base):
    """FHIR DeviceMetric resources (SRS §6.1)"""
    __tablename__ = "device_metrics"

    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    metric_name = Column(String(255), nullable=False)
    category = Column(String(50))
    operational_status = Column(String(50))
    unit = Column(String(50))
    measurement_period = Column(Float)
    fhir_resource = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DilutionWorklist(Base):
    """Automated dilution manifests (SRS §6.1)"""
    __tablename__ = "dilution_worklists"

    id = Column(Integer, primary_key=True)
    plate_id = Column(Integer, ForeignKey("plates.id"))
    sample_id = Column(String(255), nullable=False)
    initial_concentration = Column(Float, nullable=False)
    initial_unit = Column(String(50), nullable=False)
    target_concentration = Column(Float, nullable=False)
    target_unit = Column(String(50), nullable=False)
    steps = Column(JSON, nullable=False)
    total_volume_needed = Column(Float)
    molar_mass = Column(Float)
    warning_code = Column(String(100))
    is_finalized = Column(Boolean, server_default=text("false"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BarcodeIndex(Base):
    """Illumina UDI barcode dictionary (SRS §6.1, FR-3.3.4).

    Read-only after bulk load (SRS §6.1: 'Read-only after bulk load').
    Seeded from database/seeds/illumina_udis_v1.0.0.json via migration 0003.
    """
    __tablename__ = "barcode_indices"

    id = Column(Integer, primary_key=True)
    index_name = Column(String(100), nullable=False)
    index_sequence = Column(String(255), unique=True, nullable=False)
    barcode_set = Column(String(100))
    kit_type = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Plate(Base):
    """Microplate configuration (SRS §6.1 / FR-3.2)."""
    __tablename__ = "plates"

    id = Column(Integer, primary_key=True)
    plate_uid = Column(String(36), unique=True, nullable=False)
    plate_name = Column(String(255), nullable=False)
    plate_type = Column(String(50), nullable=True)
    barcode_set = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(String(255), nullable=True)
    meta = Column("metadata", JSON, nullable=True)


class PlateWell(Base):
    """Individual well state within a microplate (SRS §6.1 / FR-3.2).

    The link to an associated FHIR Observation (FR-3.2.3) is carried in
    ``meta['observation_uid']`` to avoid a schema migration; a dedicated
    column can be promoted later if query patterns require it.
    """
    __tablename__ = "plate_wells"

    id = Column(Integer, primary_key=True)
    plate_id = Column(Integer, ForeignKey("plates.id", ondelete="CASCADE"), nullable=True)
    well_row = Column(Integer, nullable=False)
    well_column = Column(Integer, nullable=False)
    well_index = Column(Integer, nullable=False)
    sample_id = Column(String(255), nullable=True)
    concentration = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    status = Column(String(50), default="pending")
    meta = Column("metadata", JSON, nullable=True)


class SimulationScenario(Base):
    """Integrated simulation scenario specification (SRS FR-3.16.1).

    Unblocks the scenario orchestrator: composes any subset of FR-3.11–FR-3.16
    with seeded parameters for reproducible, end-to-end runs.
    """
    __tablename__ = "simulation_scenarios"

    id = Column(Integer, primary_key=True)
    scenario_uid = Column(String(36), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    feature_modules = Column(JSON, nullable=False)  # e.g. ["pk_pd","chemistry","digital_twin","mrd","llm"]
    seed = Column(JSON, nullable=False)  # seeded parameters for reproducibility
    config = Column(JSON, nullable=True)  # module-specific configuration
    is_finalized = Column(Boolean, server_default=text("false"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("scenario_uid", name="uq_simulation_scenarios_uid"),
    )


class ScenarioRun(Base):
    """Executed scenario run record and aggregated outputs (SRS FR-3.16.2/3.16.3/3.16.4)."""
    __tablename__ = "scenario_runs"

    id = Column(Integer, primary_key=True)
    run_uid = Column(String(36), unique=True, nullable=False)
    scenario_id = Column(Integer, ForeignKey("simulation_scenarios.id"), nullable=True)
    seed = Column(JSON, nullable=True)  # seed actually used
    status = Column(String(50), server_default=text("'queued'"), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    aggregated_outputs = Column(JSON, nullable=True)  # collected outputs (FR-3.16.2)
    output_hashes = Column(JSON, nullable=True)  # deterministic output hashes (FR-3.16.4)
    downstream_results = Column(JSON, nullable=True)  # LIMS/EHR validation responses (FR-3.16.3)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("run_uid", name="uq_scenario_runs_uid"),
        CheckConstraint(
            status.in_(["queued", "running", "completed", "failed"]),
            name="scenario_runs_status_check",
        ),
    )


class SyntheticCohort(Base):
    """Digital twin cohort definition and member identities (SRS FR-3.13)."""
    __tablename__ = "synthetic_cohorts"

    id = Column(Integer, primary_key=True)
    cohort_uid = Column(String(36), unique=True, nullable=False)
    name = Column(String(255), nullable=True)
    size = Column(Integer, nullable=False)  # N (FR-3.13.1)
    demographic_distribution = Column(JSON, nullable=True)
    clinvar_variant_set = Column(JSON, nullable=True)  # variant set (FR-3.13.1)
    physiological_baseline_ranges = Column(JSON, nullable=True)
    members = Column(JSON, nullable=True)  # array of synthetic member identities
    is_synthetic = Column(Boolean, server_default=text("true"), nullable=False)  # FR-3.13.5
    seed = Column(JSON, nullable=True)
    scenario_run_id = Column(Integer, ForeignKey("scenario_runs.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("cohort_uid", name="uq_synthetic_cohorts_uid"),
    )


class ChemistryProfile(Base):
    """Generated clinical chemistry vectors (SRS FR-3.12)."""
    __tablename__ = "chemistry_profiles"

    id = Column(Integer, primary_key=True)
    profile_uid = Column(String(36), unique=True, nullable=False)
    simulation_id = Column(Integer, ForeignKey("simulations.id"), nullable=True)
    patient_id = Column(String(255), nullable=True)
    chemistry_vectors = Column(JSON, nullable=False)  # blood gas/electrolyte/metabolic
    clinvar_data = Column(JSON, nullable=True)  # paired variant data (FR-3.12.2)
    fhir_bundle = Column(JSON, nullable=True)  # assembled multi-modal bundle
    lims_response = Column(JSON, nullable=True)  # LIMS ingestion response
    seed = Column(JSON, nullable=True)
    scenario_run_id = Column(Integer, ForeignKey("scenario_runs.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("profile_uid", name="uq_chemistry_profiles_uid"),
    )


class PkpdWorklist(Base):
    """In silico PK/PD pipetting manifest (SRS FR-3.11)."""
    __tablename__ = "pkpd_worklists"

    id = Column(Integer, primary_key=True)
    worklist_uid = Column(String(36), unique=True, nullable=False)
    plate_id = Column(Integer, ForeignKey("plates.id"), nullable=True)
    substance_name = Column(String(255), nullable=True)  # FR-3.11.1
    pk_parameters = Column(JSON, nullable=True)  # Vd, clearance, half-life
    plasma_concentration_series = Column(JSON, nullable=True)  # FR-3.11.2
    target_matrix = Column(JSON, nullable=True)  # FR-3.11.3
    steps = Column(JSON, nullable=False)  # pipetting instructions (FR-3.11.4)
    origin = Column(String(50), server_default=text("'pk_pd_loop'"), nullable=False)
    is_finalized = Column(Boolean, server_default=text("false"), nullable=False)
    scenario_run_id = Column(Integer, ForeignKey("scenario_runs.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("worklist_uid", name="uq_pkpd_worklists_uid"),
        CheckConstraint("origin = 'pk_pd_loop'", name="pkpd_worklists_origin_check"),
    )


class CfdnaSandboxRun(Base):
    """MRD/cfDNA sandbox run and LOD results (SRS FR-3.14)."""
    __tablename__ = "cfdna_sandbox_runs"

    id = Column(Integer, primary_key=True)
    run_uid = Column(String(36), unique=True, nullable=False)
    simulation_id = Column(Integer, ForeignKey("simulations.id"), nullable=True)
    cohort_id = Column(Integer, ForeignKey("synthetic_cohorts.id"), nullable=True)
    stressor = Column(JSON, nullable=False)  # injected stressor config (FR-3.14.1)
    plasma_volume = Column(JSON, nullable=True)  # baseline & altered plasma volume
    cfdna_concentration = Column(JSON, nullable=True)  # copies/mL (FR-3.14.2)
    shedding_params = Column(JSON, nullable=True)  # theta_shed
    lod_threshold = Column(JSON, nullable=True)  # assay LOD config (FR-3.14.3)
    detection_result = Column(String(50), nullable=True)  # pass/fail/pending
    lims_response = Column(JSON, nullable=True)  # LIMS webhook verification
    scenario_run_id = Column(Integer, ForeignKey("scenario_runs.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("run_uid", name="uq_cfdna_sandbox_runs_uid"),
        CheckConstraint(
            "detection_result IS NULL OR detection_result IN ('pass', 'fail', 'pending')",
            name="cfdna_sandbox_runs_detection_result_check",
        ),
    )


class LlmRun(Base):
    """LLM invocation metadata (SRS FR-3.15)."""
    __tablename__ = "llm_runs"

    id = Column(Integer, primary_key=True)
    run_uid = Column(String(36), unique=True, nullable=False)
    provider = Column(String(100), nullable=False)  # openrouter/ollama/vllm
    model_id = Column(String(255), nullable=True)
    prompt_hash = Column(String(64), nullable=True)  # sha256 of prompt (FR-3.15.6)
    template_id = Column(String(255), nullable=True)  # RAG template used
    source_data_hash = Column(String(64), nullable=True)
    request_payload = Column(JSON, nullable=True)
    response_metadata = Column(JSON, nullable=True)
    scenario_run_id = Column(Integer, ForeignKey("scenario_runs.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("run_uid", name="uq_llm_runs_uid"),
    )


class ClinicalTextOutput(Base):
    """LLM/RAG generated narratives and reports with provenance (SRS FR-3.15.6)."""
    __tablename__ = "clinical_text_outputs"

    id = Column(Integer, primary_key=True)
    output_uid = Column(String(36), unique=True, nullable=False)
    scenario_run_id = Column(Integer, ForeignKey("scenario_runs.id"), nullable=True)
    llm_run_id = Column(Integer, ForeignKey("llm_runs.id"), nullable=True)
    text_type = Column(String(100), nullable=True)  # progress_note / pathology_report
    content = Column(Text, nullable=False)
    provenance = Column(JSON, nullable=False)  # model id, provider, prompt hash, template id, source hash
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("output_uid", name="uq_clinical_text_outputs_uid"),
    )


class RagTemplate(Base):
    """Static RAG template registry metadata (SRS FR-3.15.3, C9)."""
    __tablename__ = "rag_templates"

    id = Column(Integer, primary_key=True)
    template_id = Column(String(255), unique=True, nullable=False)
    template_name = Column(String(255), nullable=False)
    template_type = Column(String(100), nullable=True)  # cap_clia / fda_device_manual / ehr_rubric / pathology
    source_path = Column(String(512), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
