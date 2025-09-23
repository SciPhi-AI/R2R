-- R2R Enhanced Template - Supabase Setup
-- Run this SQL in your Supabase SQL editor to set up the enhanced schema

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Enhanced spreadsheet storage for Tool-Augmented Orchestration
CREATE TABLE IF NOT EXISTS spreadsheet_cells (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(255) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    row_index INTEGER NOT NULL,
    column_name VARCHAR(255) NOT NULL,
    cell_value TEXT,
    data_type VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_spreadsheet_cells_document_id ON spreadsheet_cells(document_id);
CREATE INDEX IF NOT EXISTS idx_spreadsheet_cells_filename ON spreadsheet_cells(filename);
CREATE INDEX IF NOT EXISTS idx_spreadsheet_cells_table_name ON spreadsheet_cells(table_name);
CREATE INDEX IF NOT EXISTS idx_spreadsheet_cells_column_name ON spreadsheet_cells(column_name);

-- Enhanced document metadata for better citations
CREATE TABLE IF NOT EXISTS document_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(255) UNIQUE NOT NULL,
    filename VARCHAR(255) NOT NULL,
    file_path TEXT,
    file_size BIGINT,
    mime_type VARCHAR(100),
    author VARCHAR(255),
    title VARCHAR(500),
    subject VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    modified_at TIMESTAMP WITH TIME ZONE,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    document_fingerprint VARCHAR(32),
    page_count INTEGER,
    word_count INTEGER,
    character_count INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for document metadata
CREATE INDEX IF NOT EXISTS idx_document_metadata_document_id ON document_metadata(document_id);
CREATE INDEX IF NOT EXISTS idx_document_metadata_filename ON document_metadata(filename);
CREATE INDEX IF NOT EXISTS idx_document_metadata_author ON document_metadata(author);
CREATE INDEX IF NOT EXISTS idx_document_metadata_fingerprint ON document_metadata(document_fingerprint);

-- Web search cache for performance
CREATE TABLE IF NOT EXISTS web_search_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_hash VARCHAR(64) UNIQUE NOT NULL,
    query_text TEXT NOT NULL,
    search_provider VARCHAR(50) NOT NULL,
    results JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '24 hours')
);

-- Index for web search cache
CREATE INDEX IF NOT EXISTS idx_web_search_cache_query_hash ON web_search_cache(query_hash);
CREATE INDEX IF NOT EXISTS idx_web_search_cache_expires_at ON web_search_cache(expires_at);

-- Citation tracking for audit trails
CREATE TABLE IF NOT EXISTS citation_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    citations JSONB NOT NULL,
    source_breakdown JSONB NOT NULL,
    confidence_score DECIMAL(3,2),
    web_search_used BOOLEAN DEFAULT FALSE,
    web_search_reason TEXT,
    user_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for citation log
CREATE INDEX IF NOT EXISTS idx_citation_log_user_id ON citation_log(user_id);
CREATE INDEX IF NOT EXISTS idx_citation_log_created_at ON citation_log(created_at);
CREATE INDEX IF NOT EXISTS idx_citation_log_web_search_used ON citation_log(web_search_used);

-- Row Level Security (RLS) policies
ALTER TABLE spreadsheet_cells ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE web_search_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE citation_log ENABLE ROW LEVEL SECURITY;

-- Basic RLS policies (customize based on your auth requirements)
CREATE POLICY "Users can view their own spreadsheet data" ON spreadsheet_cells
    FOR SELECT USING (auth.uid()::text = ANY(string_to_array(document_id, '-')));

CREATE POLICY "Users can view their own document metadata" ON document_metadata
    FOR SELECT USING (auth.uid()::text = ANY(string_to_array(document_id, '-')));

CREATE POLICY "Users can view web search cache" ON web_search_cache
    FOR SELECT USING (true); -- Web search cache can be shared

CREATE POLICY "Users can view their own citation logs" ON citation_log
    FOR SELECT USING (auth.uid()::text = user_id);

-- Functions for enhanced functionality

-- Function to clean up expired web search cache
CREATE OR REPLACE FUNCTION cleanup_expired_web_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM web_search_cache WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to get spreadsheet data for SQL queries
CREATE OR REPLACE FUNCTION get_spreadsheet_data(
    p_filename TEXT,
    p_columns TEXT[] DEFAULT NULL
)
RETURNS TABLE (
    row_index INTEGER,
    column_name TEXT,
    cell_value TEXT,
    data_type TEXT
) AS $$
BEGIN
    IF p_columns IS NULL THEN
        RETURN QUERY
        SELECT sc.row_index, sc.column_name, sc.cell_value, sc.data_type
        FROM spreadsheet_cells sc
        WHERE sc.filename = p_filename
        ORDER BY sc.row_index, sc.column_name;
    ELSE
        RETURN QUERY
        SELECT sc.row_index, sc.column_name, sc.cell_value, sc.data_type
        FROM spreadsheet_cells sc
        WHERE sc.filename = p_filename
        AND sc.column_name = ANY(p_columns)
        ORDER BY sc.row_index, sc.column_name;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to log citations for audit trails
CREATE OR REPLACE FUNCTION log_citation(
    p_query_text TEXT,
    p_response_text TEXT,
    p_citations JSONB,
    p_source_breakdown JSONB,
    p_confidence_score DECIMAL DEFAULT NULL,
    p_web_search_used BOOLEAN DEFAULT FALSE,
    p_web_search_reason TEXT DEFAULT NULL,
    p_user_id TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    citation_id UUID;
BEGIN
    INSERT INTO citation_log (
        query_text, response_text, citations, source_breakdown,
        confidence_score, web_search_used, web_search_reason, user_id
    ) VALUES (
        p_query_text, p_response_text, p_citations, p_source_breakdown,
        p_confidence_score, p_web_search_used, p_web_search_reason, p_user_id
    ) RETURNING id INTO citation_id;
    
    RETURN citation_id;
END;
$$ LANGUAGE plpgsql;

-- Create a scheduled job to clean up expired cache (if pg_cron is available)
-- SELECT cron.schedule('cleanup-web-cache', '0 2 * * *', 'SELECT cleanup_expired_web_cache();');

-- Grant necessary permissions
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO anon, authenticated;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'R2R Enhanced Template Supabase setup completed successfully!';
    RAISE NOTICE 'Tables created: spreadsheet_cells, document_metadata, web_search_cache, citation_log';
    RAISE NOTICE 'Functions created: cleanup_expired_web_cache, get_spreadsheet_data, log_citation';
    RAISE NOTICE 'RLS policies enabled for data security';
END $$;
