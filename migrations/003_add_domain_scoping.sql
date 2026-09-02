-- Adds a second tracked domain ("AI Agent Pulse" alongside the original "QA Pulse").
-- sources.domain and topics.domain both default to 'qa', so every existing row keeps
-- its current behavior with no backfill needed. topics.label was globally unique
-- before this; it must become unique per (label, domain) instead, or the same label
-- minted in two different domains (e.g. "Claude") would collide into one topic and
-- mix unrelated mention counts.

ALTER TABLE sources ADD COLUMN IF NOT EXISTS domain TEXT NOT NULL DEFAULT 'qa';
ALTER TABLE topics ADD COLUMN IF NOT EXISTS domain TEXT NOT NULL DEFAULT 'qa';

CREATE INDEX IF NOT EXISTS idx_topics_domain ON topics (domain);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'sources_domain_check') THEN
        ALTER TABLE sources ADD CONSTRAINT sources_domain_check CHECK (domain IN ('qa', 'agents'));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'topics_domain_check') THEN
        ALTER TABLE topics ADD CONSTRAINT topics_domain_check CHECK (domain IN ('qa', 'agents'));
    END IF;

    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'topics_label_key') THEN
        ALTER TABLE topics DROP CONSTRAINT topics_label_key;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'topics_label_domain_key') THEN
        ALTER TABLE topics ADD CONSTRAINT topics_label_domain_key UNIQUE (label, domain);
    END IF;
END $$;
