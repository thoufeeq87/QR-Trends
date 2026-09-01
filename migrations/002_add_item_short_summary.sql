-- Adds a Claude-generated ~10-word summary per item, shown in place of the raw
-- title in the dashboard's recent-items lists. Populated by tools/claude_tag_topics.py
-- at tagging time; NULL for items tagged before this migration (frontend falls back
-- to the raw title when it's NULL).

ALTER TABLE items ADD COLUMN IF NOT EXISTS short_summary TEXT;
