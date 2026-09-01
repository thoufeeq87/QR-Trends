# Workflow: Ingest Sources

## Objective
Pull new items (articles, posts, videos) from every enabled row in the `sources`
table and store them in `items`, deduped by URL.

## Required inputs
- `sources` table rows: `name`, `type` (`rss` | `reddit_json` | `hn_api` |
  `youtube_atom` | `manual`), `url`, `config` (jsonb, source-specific extras).
- `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` env vars for `reddit_json` sources (see
  Edge cases) — every other source type needs no credentials.

## Tool
`tools/fetch_source.py` — `fetch(source: Source) -> list[FetchedItem]`, dispatched by
`source.type`. Called from `app/pipeline.run_ingest()` for every row where
`enabled = true`.

## Steps
1. For each enabled source, call the matching fetcher:
   - **rss**: `feedparser.parse(source.url)` — handles both RSS 2.0 and Atom feeds
     (covers Ministry of Testing, Software Testing Help, Guru99, TestGuild blog +
     podcast, StickyMinds, BrowserStack, Sauce Labs, and YouTube channel feeds).
   - **reddit_json**: `GET https://oauth.reddit.com/r/<config.subreddit>/new` using an
     OAuth client-credentials token (see Edge cases) — the anonymous
     `www.reddit.com/.../new.json` endpoint gets hard-blocked from cloud/datacenter
     IPs like Railway's, regardless of headers.
   - **hn_api**: pull `https://hacker-news.firebaseio.com/v0/newstories.json` (capped
     to a bounded recent slice, e.g. the first 200 IDs), fetch each item, keep only
     titles matching `config.keywords` (case-insensitive substring).
   - **youtube_atom**: same as `rss` — `https://www.youtube.com/feeds/videos.xml?channel_id=<config.channel_id>`
     is a standard Atom feed `feedparser` parses natively.
   - **manual**: skip entirely (not part of automated ingestion).
2. Normalize each result to `(external_url, title, summary, published_at)`.
3. Insert into `items` with `ON CONFLICT (external_url) DO NOTHING` — this is the
   dedupe mechanism; no separate "seen" cache needed.
4. Update `sources.last_fetched_at = now()` for every source attempted (whether or not
   it returned new items), so staleness is visible even for quiet sources.

## Expected outputs
New rows in `items`. Fetch summary (`sources_checked`, `new_items`) is returned to the
caller (`app/pipeline.py`) and surfaced in `POST /api/ingest`'s response.

## Edge cases
- **Reddit blocks the anonymous JSON API from cloud/datacenter IPs (403 "Blocked"),
  not just a bad `User-Agent`.** Discovered in production on Railway: both Reddit
  sources 403'd immediately, even with a compliant custom `User-Agent`. The fix is
  OAuth, not a header tweak — `tools/fetch_source.py`'s `_get_reddit_token()` does a
  `client_credentials` grant against `https://www.reddit.com/api/v1/access_token`
  (Basic auth with `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET`, a free Reddit "script"
  app), caches the token in-process until near expiry, and all Reddit reads go
  through `oauth.reddit.com` with `Authorization: Bearer <token>`. If Reddit starts
  403ing again, check whether the app credentials are still valid before assuming
  it's a new IP block.
- **HN has no keyword-search endpoint.** Filtering happens client-side after fetching
  each story's JSON — this makes HN the most request-heavy source per run; keep the
  slice bounded (don't walk the entire firehose every day).
- **A single source failing must not abort the run.** Wrap each source's fetch in a
  try/except, log and continue — one dead feed shouldn't block the other 12.
- **`config` holds source-specific keys** (`subreddit`, `channel_id`, `keywords`) —
  see `tools/seed_sources.py` for the exact shape per source.
- **Feed URLs that don't actually exist.** Verified before seeding via `WebFetch`
  rather than assumed from a conventional URL pattern (Ministry of Testing / Test
  Tribe / Software Testing Weekly in particular were not guaranteed to have RSS —
  see `tools/seed_sources.py` for what was confirmed vs. disabled).
