# SPDX-License-Identifier: MIT
"""
SQLAlchemy ORM Models
Implements SRS §6.1 - Database Tables (ORM layer)
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, JSON, Boolean,
    ForeignKey, UniqueConstraint, CheckConstraint, ARRAY
)
from sqlalchemy.sql import func
from datetime import datetime
from database import Base


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
