-- ========================================
-- R2R PostgreSQL Initialization
-- ========================================
-- This script is automatically run when PostgreSQL container starts for the first time
-- ========================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create hatchet database for future use (if switching to full mode)
CREATE DATABASE hatchet;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE r2r TO postgres;
GRANT ALL PRIVILEGES ON DATABASE hatchet TO postgres;

-- Connect to r2r database and enable pgvector
\c r2r
CREATE EXTENSION IF NOT EXISTS vector;

-- Connect to hatchet database and enable pgvector
\c hatchet
CREATE EXTENSION IF NOT EXISTS vector;

-- Performance tuning
ALTER SYSTEM SET shared_buffers = '512MB';
ALTER SYSTEM SET effective_cache_size = '2GB';
ALTER SYSTEM SET maintenance_work_mem = '128MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '16MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';

-- pgvector optimizations
ALTER SYSTEM SET max_parallel_workers_per_gather = 2;
ALTER SYSTEM SET max_parallel_workers = 4;
