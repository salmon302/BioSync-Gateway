"""
Database Configuration Module
Implements SRS §6.1 - Database Connection
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import os

# Database URL from environment variable
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://biosync_user:biosync_secure_password@localhost:5432/biosync"
)

# TLS/SSL configuration for secure database connections
# Implements SRS NFR-S4 - Transport Layer Security
DB_SSLMODE = os.getenv("DB_SSLMODE", "prefer")  # disable, allow, prefer, require, verify-ca, verify-full
DB_SSLROOTCERT = os.getenv("DB_SSLROOTCERT")  # Path to CA certificate
DB_SSLCERT = os.getenv("DB_SSLCERT")  # Path to client certificate
DB_SSLKEY = os.getenv("DB_SSLKEY")  # Path to client key

# Build connection arguments for SSL/TLS
connect_args = {}
if DB_SSLMODE in ("require", "verify-ca", "verify-full"):
    connect_args["sslmode"] = DB_SSLMODE
    if DB_SSLROOTCERT:
        connect_args["sslrootcert"] = DB_SSLROOTCERT
    if DB_SSLCERT:
        connect_args["sslcert"] = DB_SSLCERT
    if DB_SSLKEY:
        connect_args["sslkey"] = DB_SSLKEY

# Create SQLAlchemy engine with SSL/TLS support
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,  # Set to True for SQL query logging
    connect_args=connect_args if connect_args else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for database sessions.
    Yields a database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database by creating all tables.
    Should be called on application startup for development.
    """
    Base.metadata.create_all(bind=engine)


def drop_db():
    """
    Drop all database tables.
    Use with caution - destroys all data!
    """
    Base.metadata.drop_all(bind=engine)
