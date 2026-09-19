# Workflow: Classify Trends

## Objective
Recompute each topic's trend label after every tagging pass, based on how its mention
count this week compares to its recent baseline.

## Required inputs
- `item_topics` joined with `items.fetched_at`, for every topic.

## Tool
`tools/classify_trend.py` — `recompute_all(db) -> int` (rows written), called at the
end of every `/api/ingest` run, after tagging.

## Rule
Windows are keyed on `items.fetched_at` (when QA Pulse itself first ingested the
item), **not** `items.published_at` (the source's own publish date) — see "Cold
start" below for why.

- `current_count` = distinct items tagged with this topic where `fetched_at >=
  now() - 7 days`.
- `prior_count` = distinct items tagged with this topic where `fetched_at` is in
  `[now() - 30 days, now() - 7 days)` — a 23-day window.
- Normalize the prior window to a weekly rate for a fair comparison:
  `prior_weekly_rate = prior_count * 7 / 23`.
- Then, in order:
  1. `prior_count == 0 and current_count > 0` → **new**
  2. `current_count >= prior_weekly_rate * 1.5` and `current_count >= 2` → **trending**
  3. `current_count <= prior_weekly_rate * 0.5` → **declining**
  4. otherwise → **stable**
- Thresholds (`1.5`, `0.5`, the min-2 floor on "trending") are named constants in
  `tools/classify_trend.py` — retune once real data shows how noisy low-volume topics
  are (a topic that goes 1 mention → 2 mentions shouldn't necessarily read as a 100%
  spike).

## Steps
1. Only topics with at least one mention in the last 30 days are considered — a topic
   with zero recent activity just doesn't get a `topic_trends` row (it drops out of
   all three dashboard sections, rather than being force-labeled "declining" forever).
2. For each such topic, compute `current_count`/`prior_count`, apply the rule, upsert
   into `topic_trends`.

## Expected outputs
`topic_trends` reflects every topic with recent activity, `last_updated = now()`.

## Edge cases
- **Cold start**: on the very first ~30 days of data, `prior_count` is 0 for
  everything, so every active topic classifies as "new". This is expected, not a bug —
  it resolves itself as the window fills in. Document this for whoever reviews the
  dashboard early on.
- **Why `fetched_at`, not `published_at`**: originally used `published_at`, which
  broke cold start in practice — a first-ever ingest run against a quiet feed often
  pulls its "newest" post from 2-3 weeks ago (nothing wrong with the feed, it's just
  low-traffic). By real-world publish date, that item lands straight in the *prior*
  window with nothing in *current*, so every topic reads as "declining" on day one
  instead of "new" — the opposite of the intended cold-start behavior above. Using
  `fetched_at` instead means "current week" = "items QA Pulse first saw this week,"
  which is unaffected by how old the content was when the feed happened to surface
  it, and is arguably the more honest signal for a daily-cron tracker anyway (a
  once-daily crawl of live feeds naturally sees most new posts within a day of
  publication in steady state, so this only changes behavior for backlog/cold-start
  cases, not normal operation). `app/queries.py`'s sparkline week-bucketing uses
  `fetched_at` for the same reason, so the chart's shape matches the label. Recent-
  items ordering (which posts to *show*, not counts) still uses `published_at` —
  real-world recency is the right sort for that.
- **Single-mention topics**: with `current_count >= 2` required for "trending", a
  topic that appears once won't spike into "trending" just because its prior count was
  also low — it'll read as "new" or "stable" depending on history.
