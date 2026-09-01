# Workflow: Tag Topics

## Objective
Assign 1-3 canonical QA/testing topic labels, and a short (~10-word) plain-language
summary, to every item that doesn't have either yet, using Claude.

## Required inputs
- Items from `items` with no rows in `item_topics`.
- The current list of `topics.label` (existing canonical labels), so Claude can reuse
  them instead of minting near-duplicates ("Playwright" vs "playwright automation").
- `ANTHROPIC_API_KEY` env var.

## Tool
`tools/claude_tag_topics.py` — `tag(title, summary, existing_labels) -> TopicExtraction`
(`.topics: list[str]`, `.summary: str`). One Claude call produces both outputs — the
summary isn't a second API call, just a second field on the same structured response.
Uses `client.messages.parse()` with a Pydantic output schema (Structured Outputs) so
the response is guaranteed-valid JSON, not a hand-parsed free-text reply.

Model: `claude-opus-5`. This is a per-item call at moderate daily volume (13 sources'
worth of new items); if the Anthropic bill from this step becomes a concern once real
volume is visible, the model is a single named constant in
`tools/claude_tag_topics.py` — reconsider deliberately, don't downgrade silently.

## Steps
1. For each untagged item, call `tag(item.title, item.summary, existing_labels)`.
2. `tools/claude_tag_topics.py` returns 1-3 short topic label strings plus a ~10-word
   summary.
3. Match each returned label case-insensitively against existing `topics.label` rows;
   reuse the existing topic if it matches, otherwise insert a new `topics` row.
4. Insert `item_topics` links (`ON CONFLICT (item_id, topic_id) DO NOTHING`).
5. `existing_labels` is refreshed after each new topic is created within a run, so
   later items in the same batch can reuse topics minted earlier in that same run.
6. Store the summary on `items.short_summary` — only when at least one topic was
   found (an item with zero relevant topics also gets no summary; nothing links to
   it for display anyway).

## Expected outputs
`item_topics` rows for every processed item; `topics` grows only when a genuinely new
label is needed; `items.short_summary` populated for every successfully tagged item.
The dashboard (`app/queries.py` → `common.js`) shows `short_summary` in place of the
raw title wherever it's set, falling back to the title for items tagged before this
field existed.

## Edge cases
- **API errors/timeouts**: skip the item (leave untagged), log it, continue to the
  next one — don't let one failure abort the whole tagging batch. It'll be retried on
  the next `/api/ingest` run since it's still untagged.
- **Empty/junk summary**: tag from the title alone; `tools/claude_tag_topics.py`
  handles a `None`/empty summary gracefully.
- **Label fragmentation**: this is the main failure mode to watch — if trend counts
  look artificially low for a topic that should be trending, check whether Claude is
  minting near-duplicate labels instead of reusing existing ones; tighten the system
  prompt's reuse instruction if so.
- **Rate limits**: sequential calls with the SDK's built-in retry/backoff is
  sufficient at this volume (tens of items/day, not thousands) — no batching needed
  yet. If source count or fetch frequency grows a lot, revisit with the Batches API.
- **The ~10-word summary limit is prompted, not schema-enforced** — Claude has
  reliably respected it in testing, but nothing hard-truncates a longer response if
  it ever drifts. Not worth adding validation for unless it's actually observed in
  practice.
