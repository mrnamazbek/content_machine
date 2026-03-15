-- ============================================
-- AI Content Machine — Database Schema
-- ============================================

-- Discovered trends
CREATE TABLE IF NOT EXISTS trends (
    id              SERIAL PRIMARY KEY,
    niche           VARCHAR(100) NOT NULL,
    hashtags        TEXT[],
    topic_ideas     TEXT[],
    viral_hooks     TEXT[],
    source          VARCHAR(50) DEFAULT 'perplexity',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Discovered & downloaded videos
CREATE TABLE IF NOT EXISTS videos (
    id              SERIAL PRIMARY KEY,
    source_url      VARCHAR(512) UNIQUE NOT NULL,
    source_platform VARCHAR(50) NOT NULL,  -- tiktok, instagram, youtube
    title           VARCHAR(512),
    original_views  BIGINT DEFAULT 0,
    original_likes  BIGINT DEFAULT 0,
    duration        REAL,
    hashtags        TEXT[],
    niche           VARCHAR(100),
    local_path_raw  VARCHAR(512),
    local_path_processed VARCHAR(512),
    status          VARCHAR(30) DEFAULT 'discovered',
    -- statuses: discovered -> downloaded -> processed -> captioned -> posted -> failed
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
CREATE INDEX IF NOT EXISTS idx_videos_source ON videos(source_url);
CREATE INDEX IF NOT EXISTS idx_videos_niche  ON videos(niche);

-- AI-generated captions
CREATE TABLE IF NOT EXISTS captions (
    id              SERIAL PRIMARY KEY,
    video_id        INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    caption         TEXT NOT NULL,
    hashtags        TEXT[],
    tone            VARCHAR(50) DEFAULT 'confident masculine',
    provider        VARCHAR(30),  -- openai, anthropic
    model           VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_captions_video ON captions(video_id);

-- Upload records
CREATE TABLE IF NOT EXISTS uploads (
    id              SERIAL PRIMARY KEY,
    video_id        INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    caption_id      INTEGER REFERENCES captions(id),
    platform        VARCHAR(30) NOT NULL,  -- tiktok, instagram
    method          VARCHAR(30) DEFAULT 'playwright',  -- playwright, api, manual
    post_url        VARCHAR(512),
    status          VARCHAR(30) DEFAULT 'pending',
    -- statuses: pending -> uploading -> posted -> failed
    error_message   TEXT,
    posted_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_uploads_platform ON uploads(platform);
CREATE INDEX IF NOT EXISTS idx_uploads_status   ON uploads(status);

-- Analytics snapshots
CREATE TABLE IF NOT EXISTS analytics (
    id              SERIAL PRIMARY KEY,
    upload_id       INTEGER REFERENCES uploads(id) ON DELETE CASCADE,
    views           BIGINT DEFAULT 0,
    likes           BIGINT DEFAULT 0,
    comments        BIGINT DEFAULT 0,
    shares          BIGINT DEFAULT 0,
    collected_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analytics_upload ON analytics(upload_id);

-- AI strategy reports
CREATE TABLE IF NOT EXISTS strategy_reports (
    id              SERIAL PRIMARY KEY,
    report_text     TEXT NOT NULL,
    best_topics     TEXT[],
    best_times      TEXT[],
    best_styles     TEXT[],
    provider        VARCHAR(30),
    model           VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Trigger to auto-update updated_at on videos
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_videos_updated_at
    BEFORE UPDATE ON videos
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
