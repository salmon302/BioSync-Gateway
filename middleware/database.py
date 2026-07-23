"""
Database Configuration Module
Implements SRS §6.1 - Database Connection
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError
from typing import Generator
import os
import time
import logging

logger = logging.getLogger(__name__)

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

# Reconnection settings (SRS NFR-R3: exponential backoff)
DB_RECONNECT_MAX_ATTEMPTS = int(os.getenv("DB_RECONNECT_MAX_ATTEMPTS", "5"))
DB_RECONNECT_BASE_DELAY = float(os.getenv("DB_RECONNECT_BASE_DELAY", "0.5"))
DB_RECONNECT_MAX_DELAY = float(os.getenv("DB_RECONNECT_MAX_DELAY", "30.0"))


def _exponential_backoff_delay(attempt: int) -> float:
    """Compute exponential backoff delay with jitter cap (SRS NFR-R3)."""
    delay = min(DB_RECONNECT_BASE_DELAY * (2 ** attempt), DB_RECONNECT_MAX_DELAY)
    return delay


def connect_with_backoff(engine, max_attempts: int = DB_RECONNECT_MAX_ATTEMPTS) -> bool:
    """
    Attempt to establish a connection to the database with exponential
    backoff (SRS NFR-R3). Returns True on success, False if all attempts
    are exhausted.
    """
    for attempt in range(max_attempts):
        try:
            conn = engine.connect()
            conn.close()
            return True
        except OperationalError as e:
            delay = _exponential_backoff_delay(attempt)
            logger.warning(
                f"Database connection attempt {attempt + 1}/{max_attempts} failed: {e}. "
                f"Retrying in {delay:.1f}s..."
            )
            if attempt < max_attempts - 1:
                time.sleep(delay)
    return False


# Create SQLAlchemy engine with SSL/TLS support
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=300,  # Recycle connections after 5 minutes (NFR-R3)
    echo=False,  # Set to True for SQL query logging
    connect_args=connect_args if connect_args else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative models
Base = declarative_base()


def warm_up_connection(max_attempts: int = DB_RECONNECT_MAX_ATTEMPTS) -> bool:
    """
    Warm up the connection pool with exponential backoff (NFR-R3).
    Called at application startup to fail fast if the DB is unreachable.
    """
    return connect_with_backoff(engine, max_attempts)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for database sessions.
    Yields a database session and ensures it's closed after use.
    Implements SRS NFR-R3 - connection resilience via pool_pre_ping.
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
