-- User feedback on assistant answers (run after supabase_schema.sql)
CREATE TABLE IF NOT EXISTS message_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    feedback TEXT NOT NULL CHECK (feedback IN ('up', 'down')),
    user_query TEXT NOT NULL,
    assistant_content TEXT DEFAULT '',
    thinking TEXT DEFAULT '',
    sources JSONB DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'processed', 'skipped')),
    processor_notes TEXT,
    corpus_patch JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    UNIQUE (session_id, message_id)
);

CREATE INDEX IF NOT EXISTS message_feedback_status_idx
    ON message_feedback (status, feedback, created_at DESC);
