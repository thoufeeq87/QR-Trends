-- QA Pulse initial schema
-- Applied automatically on app startup if these tables don't exist yet (see app/db.py).

CREATE TABLE IF NOT EXISTS sources (
    id              SERIAL PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,
    type            TEXT NOT NULL CHECK (type IN ('rss', 'reddit_json', 'hn_api', 'youtube_atom', 'manual')),
    url             TEXT,
    config          JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled         BOOLEAN NOT NULL DEFAULT true,
    priority        TEXT NOT NULL DEFAULT 'normal',
    last_fetched_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS items (
    id              SERIAL PRIMARY KEY,
    source_id       INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    external_url    TEXT UNIQUE NOT NULL,
    title           TEXT NOT NULL,
    summary         TEXT,
    published_at    TIMESTAMPTZ NOT NULL,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_items_published_at ON items (published_at);
CREATE INDEX IF NOT EXISTS idx_items_source_id ON items (source_id);

CREATE TABLE IF NOT EXISTS topics (
    id              SERIAL PRIMARY KEY,
    label           TEXT UNIQUE NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS item_topics (
    id              SERIAL PRIMARY KEY,
    item_id         INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    topic_id        INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (item_id, topic_id)
);

CREATE INDEX IF NOT EXISTS idx_item_topics_topic_id ON item_topics (topic_id);

CREATE TABLE IF NOT EXISTS topic_trends (
    topic_id        INTEGER PRIMARY KEY REFERENCES topics(id) ON DELETE CASCADE,
    current_count   INTEGER NOT NULL DEFAULT 0,
    prior_count     INTEGER NOT NULL DEFAULT 0,
    trend_label     TEXT NOT NULL CHECK (trend_label IN ('new', 'trending', 'stable', 'declining')),
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT now()
);
