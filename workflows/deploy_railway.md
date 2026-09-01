# Workflow: Deploy to Railway

## Objective
Get QA Pulse's web app, Postgres database, and daily ingest cron live on Railway. This
is a manual runbook (executed by the project owner, not automated by the agent — no
Railway account access was available in the dev sandbox this app was built in).

## Required inputs
- A Railway account with billing set up (Postgres + two services isn't free-tier
  forever, though it fits comfortably in Railway's free/hobby tier at this scale).
- This repo pushed to GitHub, connected to a new Railway project.
- An Anthropic API key.

## Steps

### 1. Create the project and web service
1. In Railway, "New Project" → "Deploy from GitHub repo" → select this repo.
2. Railway should auto-detect Python via `requirements.txt` + `railway.json`
   (Nixpacks builder, start command `uvicorn app.main:app --host 0.0.0.0 --port
   $PORT`). If it doesn't pick up `railway.json` automatically, set the start command
   manually in the service's Settings → Deploy.
3. Rename the service to something clear, e.g. `qa-pulse-web`.

### 2. Add Postgres
1. In the same project, "New" → "Database" → "Add PostgreSQL".
2. Railway auto-injects `DATABASE_URL` into every service in the project — the web
   service's `app/config.py` reads it directly, no manual wiring needed.

### 3. Set web service environment variables
In `qa-pulse-web` → Variables, add:
- `ANTHROPIC_API_KEY` — your Anthropic API key.
- `INGEST_SECRET` — any long random string (e.g. `openssl rand -hex 32`). This is the
  shared secret the cron service uses to call `/api/ingest`.
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` — from a free Reddit "script" app
  (create one at https://www.reddit.com/prefs/apps). Required for the two Reddit
  sources — Reddit's anonymous JSON API hard-blocks Railway's IPs regardless of
  headers, so this isn't optional in production (see `workflows/ingest_sources.md`
  Edge cases).

`DATABASE_URL` and `PORT` are already provided by Railway.

### 4. First deploy + schema
Deploy the service. `app/main.py`'s startup hook (`ensure_schema()`) applies
`migrations/001_init.sql` automatically the first time it runs against an empty
database — no manual migration step. Confirm it worked: `GET
https://<your-app>.up.railway.app/api/health` should return `{"status": "ok"}`.

Then seed the sources table once via Railway's one-off command runner (Settings → or
`railway run` from the CLI if you have it installed locally):
```
railway run python -m tools.seed_sources
```
This seeds all 13 sources, most `enabled=false` because their feed URLs weren't
live-verified during development (see `tools/seed_sources.py`'s module docstring and
"Verifying source URLs" below) — flip `enabled` to `true` in the `sources` table for
any you've confirmed work.

### 5. Create the ingest-cron service
1. "New" → "GitHub Repo" → same repo, as a second service in the same project.
2. Rename it `qa-pulse-ingest-cron`.
3. Settings → Deploy → override the start command to:
   `python tools/trigger_ingest.py`
4. Settings → Cron Schedule → `0 6 * * *` (daily at 06:00 UTC — adjust as you like).
5. Variables for this service:
   - `INGEST_SECRET` — the same value as the web service.
   - `WEB_URL` — the web service's Railway-provided URL (its public domain, or the
     internal `*.railway.internal` address if both services are in the same project —
     internal networking avoids a public round-trip for a same-project call).

### 6. Verify
- Trigger the cron service manually once (Railway's "Run now" if available, or `curl
  -X POST -H "X-Ingest-Secret: <secret>" https://<web-url>/api/ingest` yourself) and
  check the response summary (`sources_checked`, `new_items`, `items_tagged`,
  `topics_updated`).
- Open the web URL and confirm the dashboard loads (it'll be mostly/entirely empty
  after just one run — see Edge cases).

## Verifying source URLs
Development happened in a network-restricted sandbox (only package registries and
`api.anthropic.com` were reachable — see `tools/seed_sources.py`), so most of the 13
sources' feed URLs are seeded but unverified. After the first cron run, check the
`qa-pulse-web` service logs for `fetch failed for source ...` entries — each failing
source is logged with its name and type, so you can tell which URLs need fixing
without guessing. Fix the `url` (or `config`) column in the `sources` table directly,
or update `tools/seed_sources.py` and re-run the seed script (it's an upsert by
`name`, safe to re-run).

## Edge cases
- **Cold start**: the first ~30 days show almost everything as "new" (see
  `workflows/classify_trends.md`) — this is expected, not a deploy problem.
- **Railway's filesystem is ephemeral** between deploys — matches this repo's existing
  `.tmp/` convention (nothing there is expected to survive). All real state lives in
  Postgres.
- **Ingest takes a while**: with Claude tagging running per-item, a run with many new
  items can take a couple of minutes. `tools/trigger_ingest.py` uses a 120s timeout —
  raise it if runs start timing out as more sources get enabled.
