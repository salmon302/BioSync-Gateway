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
# Implements SRS NFR-S4 (TLS) and NFR-S5 (DB client-certificate auth).
#
# Default sslmode is environment-aware (R2 remediation):
#   * ENVIRONMENT=production  -> "verify-full"  (enforces mutual-TLS to
#     PostgreSQL: server cert verified AND client cert presented, satisfying
#     NFR-S5 "client-cert auth in addition to password"). Fail-closed.
#   * any other value (development/test/CI) -> "prefer" so local/CI stacks
#     without a PKI still connect; TLS is still attempted and used when the
#     server offers it.
# The default is always overridable via DB_SSLMODE (e.g. set "disable" for a
# bare local Postgres with no TLS).
_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
_DB_SSLMODE_DEFAULT = "verify-full" if _ENVIRONMENT == "production" else "prefer"
DB_SSLMODE = os.getenv("DB_SSLMODE", _DB_SSLMODE_DEFAULT)
DB_SSLROOTCERT = os.getenv("DB_SSLROOTCERT")  # Path to CA certificate
DB_SSLCERT = os.getenv("DB_SSLCERT")  # Path to client certificate
DB_SSLKEY = os.getenv("DB_SSLKEY")  # Path to client key

if DB_SSLMODE in ("verify-ca", "verify-full"):
    logger.info(
        "Database TLS enforced: sslmode=%s (client-cert mutual-TLS active for NFR-S5)",
        DB_SSLMODE,
    )
    if not DB_SSLROOTCERT and DB_SSLMODE == "verify-full":
        logger.warning(
            "DB_SSLMODE=verify-full but DB_SSLROOTCERT is unset; the server "
            "certificate will be verified against the system CA bundle. Set "
            "DB_SSLROOTCERT to the BioSync CA (certs/ca.crt) for mutual-TLS."
        )
elif _ENVIRONMENT == "production":
    logger.warning(
        "ENVIRONMENT=production but DB_SSLMODE=%s (not verify-full). Database "
        "connections are NOT using mutual-TLS. Set DB_SSLMODE=verify-full for "
        "NFR-S5 compliance.", DB_SSLMODE,
    )

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
