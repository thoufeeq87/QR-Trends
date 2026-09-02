# QA Pulse — Development Plan (PRD)

## Overview

**QA Pulse** is a full-stack app that tracks what topics are trending, stable, or
fading — across two independently tracked domains from one deployment: **QA Pulse**
(software QA/testing, the original domain) and **AI Agent Pulse** (AI agents /
agentic AI, added later). It ingests articles, forum posts, and videos from ~27
sources daily across both domains, uses Claude to extract domain-scoped topic labels,
classifies each topic's momentum (New / Trending / Stable / Declining) based on
recent mention counts, and surfaces the result on a dashboard with a header dropdown
to switch which domain is shown. It's built around the **WAT framework** established
in this repo's foundation phase (see below) and deploys to Railway.

This is a living document — the sections below reflect the current build; see Roadmap
for what's still open.

## Architecture: the WAT Framework

QA Pulse is built around the **WAT framework** (Workflows, Agents, Tools). The idea:
keep probabilistic reasoning (the AI agent) separate from deterministic execution
(scripts), so the system stays reliable. If each step in a chain is only ~90% reliable,
five AI-driven steps in a row compound down to ~59% success — offloading execution to
tested, deterministic tools avoids that decay.

### Layer 1: Workflows (`workflows/`)
Markdown SOPs, one per pipeline stage: `ingest_sources.md`, `tag_topics.md`,
`classify_trends.md`, `deploy_railway.md`. Each defines the objective, required
inputs, which tool to use, expected outputs, and edge cases.

### Layer 2: Agent (Claude Code)
Reads the relevant workflow before acting, runs tools in sequence, handles failures
gracefully. For QA Pulse specifically, the ingestion/tagging/classification tools also
ship *inside the deployed app* and run on Railway's own cron — the agent's role during
development was to design and validate the pipeline, not to be a runtime component of
it.

### Layer 3: Tools (`tools/`)
Python scripts doing the actual work — fetching sources, calling Claude, computing
trend labels. See each workflow doc for the matching tool.

## Directory Layout

```
QR-Trends/
├── app/                      # FastAPI app (routes, DB models, pipeline orchestration)
│   ├── main.py, config.py, db.py, queries.py, schemas.py, pipeline.py
│   └── static/                # dashboard (plain HTML/JS/CSS, no build step)
├── tools/                     # fetch_source.py, claude_tag_topics.py, classify_trend.py,
│                               # seed_sources.py, trigger_ingest.py
├── workflows/                 # ingest_sources.md, tag_topics.md, classify_trends.md,
│                               # deploy_railway.md
├── migrations/001_init.sql    # DB schema, applied automatically on first startup
├── scripts/run_pipeline_local.py  # local dev validation helper
├── docs/PRD.md                 # this file
├── railway.json, requirements.txt, .env.example, .gitignore
└── CLAUDE.md
```

**Intermediates vs. deliverables:** `.tmp/` (and Railway's ephemeral filesystem
generally) is disposable — the live Railway URL (app + Postgres) is the deliverable,
the same role a Google Sheet plays in the original WAT example.

## Tech stack

- **Backend**: Python + FastAPI (single service) — chosen over Node to stay
  consistent with this repo's existing `tools/` = Python convention.
- **Database**: PostgreSQL via Railway's Postgres plugin (`DATABASE_URL` auto-injected).
- **Scheduler**: a second Railway service (`qa-pulse-ingest-cron`) on a Cron Schedule,
  calling the main service's protected `POST /api/ingest`.
- **Frontend**: static single-page dashboard (HTML/JS/CSS, no build step), served by
  FastAPI's `StaticFiles`.
- **AI**: Anthropic API (`claude-opus-5`) for topic extraction via
  `client.messages.parse()` structured outputs.

## Data model

`sources` (config per source) → `items` (fetched, deduped by URL) → `item_topics`
(Claude-assigned labels, linking to canonical `topics`) → `topic_trends` (recomputed
trend label per topic). Full schema: `migrations/001_init.sql`, plus incremental
migrations under `migrations/` (`ensure_schema()` applies every file there, in order,
on every startup — see `app/db.py`).

**Domains**: `sources.domain` and `topics.domain` (`'qa'` | `'agents'`,
`migrations/003_add_domain_scoping.sql`) scope both ingestion sources and the topic
pool they feed. `topics` is unique per `(label, domain)`, not globally — the same
label minted from a `qa` item and an `agents` item lands in two separate rows, so
mention counts and recent items never mix across domains. Every domain-facing query
(`app/queries.py`, `GET /api/topics`, `GET /api/status`) takes a `domain` param
(default `'qa'`).

## Trend classification rule

`current_count` = mentions in the last 7 days; `prior_count` = mentions in the prior
23-day window (day 8–30). Normalized to a weekly rate for comparison; New / Trending /
Stable / Declining thresholds are named constants in `tools/classify_trend.py`. Full
rule: `workflows/classify_trends.md`.

## Conventions

Unchanged from the foundation phase: tools-first (check `tools/` before writing a new
script), the self-improvement loop on failures (fix → verify → update the workflow),
workflows are living instructions (update, don't casually overwrite), secrets only in
`.env`/Railway env vars, never committed.

## Roadmap / Phases

- **Phase 0 — Foundation**: WAT scaffold. Done.
- **Phase 1 — Core pipeline**: schema, ingestion (4 source types: RSS/Atom, Reddit
  JSON, HN API, manual), Claude tagging, trend classification, dashboard. Done —
  validated locally end-to-end against a local Postgres instance, including a real
  Claude API call (correct topic extraction and topic reuse across items) and all four
  trend-classification buckets (new/trending/stable/declining) (see
  `scripts/run_pipeline_local.py`).
- **Phase 2 — Full source list**: all 13 sources seeded in `sources`
  (`tools/seed_sources.py`). Most are `enabled=false` pending URL verification — the
  dev sandbox this was built in has network egress restricted to package registries +
  `api.anthropic.com`, so feed URLs beyond Reddit's and HN's stable public APIs
  weren't live-verified. See "Verifying source URLs" in
  `workflows/deploy_railway.md` for how to confirm/enable the rest post-deploy.
- **Phase 3 — Railway deployment**: code is deploy-ready (`railway.json`, startup
  migration runner, `tools/trigger_ingest.py`). Actual deployment is a manual runbook
  (`workflows/deploy_railway.md`) — the dev sandbox has no Railway account access.
- **Phase 4 — AI Agent Pulse (second domain)**: `sources`/`topics` gained a `domain`
  column (`qa` | `agents`), topic uniqueness is now per-domain, pipeline/tagging/API
  are domain-aware, and the dashboard header has a `<select>` to switch domains
  (persisted to `localStorage`). 6 new sources seeded under `domain='agents'`:
  r/AI_Agents, r/ClaudeAI, r/LocalLLaMA (Reddit RSS), CrewAI Community Forum (RSS,
  unverified), MCP GitHub releases (Atom, unverified), and a second `hn_api` source
  filtered by agent keywords. Two originally-proposed sources (Anthropic Discord,
  Latent Space Discord) were dropped — no RSS/public API for reading messages, and a
  bot needs admin access to servers this project doesn't run. Cross-domain topic
  isolation confirmed locally (see `workflows/tag_topics.md` "Domains"); URL
  verification for the two unverified `agents` sources is pending, same as several
  `qa`-domain sources in Phase 2.

## Open questions / known gaps

- Most non-Reddit/HN source URLs need verification once deployed (see Phase 2),
  including the `agents`-domain CrewAI forum and MCP GitHub releases URLs (Phase 4).
- YouTube channel IDs for the 4 named channels weren't resolved (no reliable way to
  look them up from this sandbox) — seeded as disabled with a note; needs a manual
  channel ID lookup before enabling.
- Trend classification thresholds (1.5x / 0.5x / min-2-for-trending) are a first pass
  — retune once real mention-volume data is visible.
- ~~No auth on the dashboard itself~~ — the dashboard now requires Google sign-in,
  restricted to specific Gmail address(es) via `ALLOWED_EMAILS` (see `app/auth.py`,
  `workflows/deploy_railway.md` "Google Sign-In setup"). `/api/ingest` and
  `/api/health` keep their own separate, non-human auth (secret header / none) since
  they're called by the cron service and infra monitoring, not a signed-in user.
