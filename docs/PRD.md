# QR-Trends — Development Plan (PRD)

## Overview

**QR-Trends** is a new project. Its specific product scope (what it actually does for
end users) has not been defined yet — that will be supplied in a follow-up. This
document currently covers the **foundation phase only**: the technical architecture and
conventions the project will be built on, so that once the product requirements arrive
there is a working structure to build them into.

This is a living document. Sections marked **TBD** will be filled in once product scope
is confirmed.

## Architecture: the WAT Framework

QR-Trends is built around the **WAT framework** (Workflows, Agents, Tools). The idea:
keep probabilistic reasoning (the AI agent) separate from deterministic execution
(scripts), so the system stays reliable. If each step in a chain is only ~90% reliable,
five AI-driven steps in a row compound down to ~59% success — offloading execution to
tested, deterministic tools avoids that decay.

### Layer 1: Workflows (`workflows/`)
Markdown SOPs, one per task the agent needs to perform. Each workflow defines:
- The objective
- Required inputs
- Which tool(s) to use, in what order
- Expected outputs
- How to handle edge cases / known failure modes

Written in plain language, the way you'd brief a teammate — not code.

### Layer 2: Agent (Claude Code)
The agent is the decision-maker, not the executor:
- Reads the relevant workflow for a given task
- Determines required inputs, runs tools in the correct sequence
- Handles failures gracefully, asks clarifying questions when something is ambiguous
- Connects intent to execution without trying to hand-roll the work itself — e.g. to
  pull data from a website, it reads `workflows/scrape_website.md`, gathers the inputs
  that workflow calls for, then runs the matching script in `tools/`, rather than
  scraping ad hoc.

### Layer 3: Tools (`tools/`)
Python scripts that do the actual work: API calls, data transformations, file
operations, database queries. Consistent, testable, fast — and the first place to look
before writing anything new (see Conventions below).

## Directory Layout

```
QR-Trends/
├── docs/
│   └── PRD.md          # this file
├── workflows/           # Markdown SOPs (empty until product workflows are defined)
├── tools/                # Python scripts for deterministic execution (empty for now)
├── .tmp/                 # Scratch/intermediate files — disposable, regenerated as needed
├── .env.example          # Documents expected env vars; real .env is never committed
├── .gitignore
├── CLAUDE.md             # Repo-level agent instructions (WAT operating rules)
└── README.md
```

**Intermediates vs. deliverables:** anything in `.tmp/` is disposable working data and
must never be treated as a source of truth. Real outputs surface in the **web
dashboard** (the confirmed delivery target for this project) rather than as files
committed to the repo.

## Conventions

- **Tools-first:** before writing a new script, check `tools/` for something that
  already does the job. Only add a new tool when nothing existing covers the task.
- **Self-improvement loop**, run whenever something breaks:
  1. Identify what broke (read the full error/trace)
  2. Fix the tool (check in before retrying anything that costs money/credits)
  3. Verify the fix actually works
  4. Update the relevant workflow with what was learned (rate limits, timing quirks,
     unexpected behavior) so the same failure doesn't recur
  5. Move on with a more robust system
- **Workflows are living instructions**, not disposable notes — update them as better
  methods or constraints are discovered, but don't create or overwrite one without
  checking first; they represent agreed process, not a scratchpad.
- **Secrets:** all credentials/API keys live in `.env` (gitignored) — never hardcoded,
  never committed elsewhere. OAuth artifacts (`credentials.json`, `token.json`) are
  gitignored for the same reason.

## Roadmap / Phases

- **Phase 0 — Foundation (this plan):** WAT scaffold in place
  (`workflows/`, `tools/`, `.tmp/`, `.env.example`, `.gitignore`, `CLAUDE.md`,
  `docs/PRD.md`). No product logic yet.
- **Phase 1 — Product definition:** **TBD.** Pending the actual QR-Trends product scope
  (what it tracks, who it's for, what data sources it needs). This PRD will be updated
  with concrete objectives, user stories, and success criteria once that's confirmed.
- **Phase 2 — Core workflows & tools:** **TBD.** Build out the specific
  `workflows/*.md` SOPs and matching `tools/*.py` scripts once Phase 1 defines what
  needs to happen.
- **Phase 3 — Dashboard:** **TBD.** Stand up the web dashboard that surfaces the
  processed data/trends to the user (tech stack not yet chosen).

## Open Questions (not yet decided)

- What does QR-Trends actually track or generate for the end user?
- Who is the target user (individual, business, internal tool)?
- What are the data sources / inputs (scraping, an API, user uploads, QR scan events)?
- What tech stack should the dashboard and tool scripts use?
- Any external services/credentials to plan for in `.env` (e.g. a QR generation
  library/API, an analytics data source)?

These will be resolved before Phase 1 work starts.
