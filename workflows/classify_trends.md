# Workflow: Classify Trends

## Objective
Recompute each topic's trend label after every tagging pass, based on how its mention
count this week compares to its recent baseline.

## Required inputs
- `item_topics` joined with `items.published_at`, for every topic.

## Tool
`tools/classify_trend.py` — `recompute_all(db) -> int` (rows written), called at the
end of every `/api/ingest` run, after tagging.

## Rule
- `current_count` = distinct items tagged with this topic where `published_at >=
  now() - 7 days`.
- `prior_count` = distinct items tagged with this topic where `published_at` is in
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
- **Single-mention topics**: with `current_count >= 2` required for "trending", a
  topic that appears once won't spike into "trending" just because its prior count was
  also low — it'll read as "new" or "stable" depending on history.
