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
   $PORT --proxy-headers --forwarded-allow-ips=*` — the proxy flags matter for Google
   sign-in below: without them, uvicorn doesn't know the request arrived over HTTPS
   at Railway's edge, and generates an `http://` redirect URI that Google will
   reject). If it doesn't pick up `railway.json` automatically, set the start command
   manually in the service's Settings → Deploy.
3. Rename the service to something clear, e.g. `qa-pulse-web`.

### 2. Add Postgres
1. In the same project, "New" → "Database" → "Add PostgreSQL".
2. Railway auto-injects `DATABASE_URL` into every service in the project — the web
   service's `app/config.py` reads it directly, no manual wiring needed.

### 3. Google Sign-In setup
The dashboard requires Google sign-in, restricted to specific Gmail address(es) —
signing in with Google alone only proves *a* Google account; the allowlist
(`ALLOWED_EMAILS`) is what actually restricts it to you. To get the credentials this
needs:
1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create or select
   a project.
2. **APIs & Services → OAuth consent screen**: User type **External**, publishing
   status **Testing** (this is a personal single-owner tool — Testing mode skips
   Google's app-verification review entirely and is the right choice here, not
   "In production"). Add your Gmail address under **Test users** — in Testing mode,
   Google rejects sign-in from anyone not explicitly listed here, which is actually a
   second, Google-side layer of the same restriction `ALLOWED_EMAILS` enforces
   app-side.
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID** →
   Application type **Web application**. Under **Authorized redirect URIs**, add
   `https://<your-web-service>.up.railway.app/auth/callback` (and, if you want to
   test sign-in locally too, `http://localhost:8000/auth/callback`).
4. Copy the **Client ID** and **Client secret** it gives you.

### 4. Set web service environment variables
In `qa-pulse-web` → Variables, add:
- `ANTHROPIC_API_KEY` — your Anthropic API key.
- `INGEST_SECRET` — any long random string (e.g. `openssl rand -hex 32`). This is the
  shared secret the cron service uses to call `/api/ingest`.
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — from step 3 above.
- `SESSION_SECRET_KEY` — any long random string (e.g. `openssl rand -hex 32`).
  **Must** be set explicitly — without it the app generates a random one on every
  boot, silently logging everyone out on each deploy or restart.
- `ALLOWED_EMAILS` — your Gmail address (comma-separated if more than one). This is
  the actual access control; anyone else who successfully signs in with Google still
  gets a 403.
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` — not currently needed. Reddit's
  anonymous JSON API blocks Railway's IPs, and their classic script-app credential
  flow now redirects to a Devvit developer-platform signup instead of issuing
  credentials, so the two Reddit sources run as `type=rss` against Reddit's own feed
  instead (see `workflows/ingest_sources.md` Edge cases — unverified, check ingest
  logs). Only set these and switch those sources back to `type=reddit_json` if the
  RSS fallback also gets blocked and someone completes the Devvit signup.

`DATABASE_URL` and `PORT` are already provided by Railway.

### 5. First deploy + schema
Deploy the service. `app/main.py`'s startup hook (`ensure_schema()`) applies
`migrations/001_init.sql` automatically the first time it runs against an empty
database — no manual migration step. Confirm it worked: `GET
https://<your-app>.up.railway.app/api/health` should return `{"status": "ok"}` — this
endpoint is deliberately exempt from Google sign-in (needed for Railway/monitoring to
check it). Visiting the web URL itself in a browser should now redirect to
`/login.html` — try signing in with your Gmail address to confirm the whole chain
(Google Cloud Console config → env vars → app) actually works end to end.

Then seed the sources table once via Railway's one-off command runner (Settings → or
`railway run` from the CLI if you have it installed locally):
```
railway run python -m tools.seed_sources
```
This seeds all 13 sources, most `enabled=false` because their feed URLs weren't
live-verified during development (see `tools/seed_sources.py`'s module docstring and
"Verifying source URLs" below) — flip `enabled` to `true` in the `sources` table for
any you've confirmed work.

### 6. Create the ingest-cron service
This service calls `/api/ingest` directly with the shared secret — it never goes
through Google sign-in (and shouldn't; it's not a human), so nothing here changes
because of the login feature.
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

### 7. Verify
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
- **Revoking access**: removing an email from `ALLOWED_EMAILS` and redeploying
  revokes that person's *existing* signed-in session too, not just future logins —
  `AuthMiddleware` re-checks the allowlist on every request, not only at sign-in.
- **`SESSION_SECRET_KEY` must be set explicitly.** If it's missing, the app still
  boots (falls back to a random key so local dev isn't blocked), but that means every
  deploy or restart invalidates all sessions — everyone gets logged out. Set it once
  in Railway and leave it alone.
- **OAuth consent screen in "Testing" mode caps at 100 test users** and only lets
  explicitly-added test users sign in at all (Google rejects anyone else before your
  app even sees them) — a second, Google-side version of the same restriction
  `ALLOWED_EMAILS` enforces app-side. Fine for a single-owner tool; if this ever needs
  more than 100 users, that's when "In production" + Google's verification review
  would become necessary — not before.
