-- Run this in Supabase SQL Editor before starting the app

-- Enable pgvector extension (may already be enabled from smart-ai-agent)
CREATE EXTENSION IF NOT EXISTS vector;

-- Financial documents table
-- Uses 1024 dimensions — Amazon Titan Embeddings V2
CREATE TABLE IF NOT EXISTS financial_documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content     TEXT NOT NULL,
    source      TEXT NOT NULL,
    doc_type    TEXT DEFAULT 'financial_report',
    chunk_index INTEGER DEFAULT 0,
    embedding   VECTOR(1024),           -- Titan V2 = 1024 dimensions
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Approximate-nearest-neighbour index for fast cosine similarity search.
-- HNSW gives better recall/latency than ivfflat and needs no `lists` tuning.
CREATE INDEX IF NOT EXISTS financial_docs_embedding_idx
    ON financial_documents
    USING hnsw (embedding vector_cosine_ops);

-- Index for source lookups
CREATE INDEX IF NOT EXISTS financial_docs_source_idx
    ON financial_documents (source);

-- Server-side similarity search. The app calls this via supabase.rpc() so the
-- ranking runs inside Postgres against the HNSW index instead of pulling every
-- row to the client and scoring in Python.
--   <=> is the pgvector cosine-distance operator; similarity = 1 - distance.
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding VECTOR(1024),
    match_count INT DEFAULT 4
)
RETURNS TABLE (content TEXT, source TEXT, similarity FLOAT)
LANGUAGE sql STABLE
AS $$
    SELECT
        content,
        source,
        1 - (embedding <=> query_embedding) AS similarity
    FROM financial_documents
    ORDER BY embedding <=> query_embedding
    LIMIT match_count;
$$;

-- Enable Row Level Security
ALTER TABLE financial_documents ENABLE ROW LEVEL SECURITY;

-- Allow anon access (same pattern as smart-ai-agent)
CREATE POLICY "Allow anon access" ON financial_documents
    FOR ALL TO anon
    USING (true)
    WITH CHECK (true);

-- Verify setup
SELECT 'financial_documents table ready' AS status;
SELECT COUNT(*) AS existing_documents FROM financial_documents;
