-- Enable pgvector extension for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- Financial research document store with embeddings
CREATE TABLE IF NOT EXISTS financial_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    embedding vector(1024),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for fast approximate nearest-neighbor search
CREATE INDEX IF NOT EXISTS financial_documents_embedding_idx
    ON financial_documents
    USING hnsw (embedding vector_cosine_ops);

-- GIN index for metadata filtering (ticker, sector, source, etc.)
CREATE INDEX IF NOT EXISTS financial_documents_metadata_idx
    ON financial_documents
    USING gin (metadata);

-- Match function used by LlamaIndex SupabaseVectorStore
CREATE OR REPLACE FUNCTION match_financial_documents(
    query_embedding vector(1024),
    match_count int DEFAULT 5,
    filter jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    metadata JSONB,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        fd.id,
        fd.content,
        fd.metadata,
        1 - (fd.embedding <=> query_embedding) AS similarity
    FROM financial_documents fd
    WHERE fd.metadata @> filter
    ORDER BY fd.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- User feedback on answers: run backend/supabase_feedback.sql
-- Initial documents are loaded via /api/ingest from backend/data/corpus.json
-- INSERT INTO financial_documents (content, metadata) VALUES
-- ('Apple Inc. reported Q4 revenue of $94.9B...', '{"ticker": "AAPL", "sector": "Technology", "source": "10-K"}');
