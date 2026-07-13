-- Enable pgcrypto extension for cryptographic hash functions
-- Required for hash chain implementation (SRS FR-3.8.3)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable JSONB indexing support
CREATE EXTENSION IF NOT EXISTS btree_gin;
